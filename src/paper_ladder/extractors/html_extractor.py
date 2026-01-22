"""HTML content extractor for Paper-Ladder."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from paper_ladder.extractors.base import BaseExtractor
from paper_ladder.models import ExtractedContent
from paper_ladder.utils import clean_html_text, is_valid_url


class HTMLExtractor(BaseExtractor):
    """HTML content extractor using BeautifulSoup.

    Extracts article content from HTML pages with support for
    common academic publishing formats.
    """

    name = "html"
    supported_extensions = ["html", "htm"]

    # Common selectors for article content
    CONTENT_SELECTORS = [
        "article",
        "[role='main']",
        ".article-content",
        ".paper-content",
        ".full-text",
        ".content-body",
        "#article-body",
        "#main-content",
        "main",
    ]

    # Selectors to remove (ads, navigation, etc.)
    REMOVE_SELECTORS = [
        "nav",
        "header",
        "footer",
        "aside",
        ".sidebar",
        ".advertisement",
        ".ads",
        ".cookie-banner",
        ".nav",
        ".menu",
        ".social-share",
        ".related-articles",
        "script",
        "style",
        "noscript",
    ]

    def can_handle(self, source: str | Path) -> bool:
        """Check if this extractor can handle the given source.

        Args:
            source: URL or file path to check.

        Returns:
            True if this is an HTML file or URL.
        """
        source_str = str(source).lower()
        ext = self._get_extension(source)

        # HTML file
        if ext in self.supported_extensions:
            return True

        # URL that's likely HTML (not PDF or other binary)
        if is_valid_url(source_str):
            return not any(
                source_str.endswith(f".{e}")
                for e in ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"]
            )

        return False

    async def extract(
        self,
        source: str | Path,
        **kwargs: object,
    ) -> ExtractedContent:
        """Extract content from an HTML file or URL.

        Args:
            source: URL or file path to the HTML.
            **kwargs: Additional parameters.

        Returns:
            ExtractedContent with markdown and extracted elements.
        """
        source_str = str(source)

        # Get HTML content
        if is_valid_url(source_str):
            html = await self._fetch_html(source_str)
            source_type = "html_url"
        else:
            html = Path(source).read_text(encoding="utf-8")
            source_type = "html_file"

        # Parse and extract
        result = self._extract_from_html(html)

        return ExtractedContent(
            markdown=result["markdown"],
            metadata=result.get("metadata", {}),
            figures=result.get("figures", []),
            tables=result.get("tables", []),
            source_url=source_str if is_valid_url(source_str) else None,
            source_type=source_type,
        )

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL.

        Args:
            url: URL to fetch.

        Returns:
            HTML content as string.
        """
        kwargs: dict[str, object] = {
            "timeout": self.config.request_timeout,
            "follow_redirects": True,
        }
        proxy = self.config.get_proxy_url()
        if proxy:
            kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**kwargs) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_from_html(self, html: str) -> dict[str, Any]:
        """Extract structured content from HTML.

        Args:
            html: HTML content string.

        Returns:
            Dict with markdown, metadata, figures, and tables.
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract metadata
        metadata = self._extract_metadata(soup)

        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Find main content
        content = None
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                break

        # Fall back to body if no content found
        if not content:
            content = soup.body or soup

        # Extract figures
        figures = self._extract_figures(content)

        # Extract tables
        tables = self._extract_tables(content)

        # Convert to markdown
        markdown = self._html_to_markdown(content)

        return {
            "markdown": markdown,
            "metadata": metadata,
            "figures": figures,
            "tables": tables,
        }

    def _extract_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract metadata from HTML head.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Dict of metadata.
        """
        metadata: dict[str, Any] = {}

        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = clean_html_text(title_tag.get_text())

        # Meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            property_attr = meta.get("property", "").lower()
            content = meta.get("content", "")

            if name == "author" or property_attr == "article:author":
                metadata["author"] = content
            elif name == "description" or property_attr == "og:description":
                metadata["description"] = content
            elif name == "keywords":
                metadata["keywords"] = [k.strip() for k in content.split(",")]
            elif name == "citation_doi":
                metadata["doi"] = content
            elif name == "citation_title":
                metadata["title"] = content
            elif name == "citation_author":
                if "authors" not in metadata:
                    metadata["authors"] = []
                metadata["authors"].append(content)
            elif name == "citation_publication_date":
                metadata["publication_date"] = content

        return metadata

    def _extract_figures(self, content: Tag | BeautifulSoup) -> list[str]:
        """Extract figure URLs from content.

        Args:
            content: BeautifulSoup Tag or object.

        Returns:
            List of figure URLs.
        """
        figures = []

        for img in content.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                figures.append(src)

        for figure in content.find_all("figure"):
            img = figure.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src and src not in figures:
                    figures.append(src)

        return figures

    def _extract_tables(self, content: Tag | BeautifulSoup) -> list[str]:
        """Extract tables as HTML strings.

        Args:
            content: BeautifulSoup Tag or object.

        Returns:
            List of table HTML strings.
        """
        tables = []

        for table in content.find_all("table"):
            tables.append(str(table))

        return tables

    def _html_to_markdown(self, content: Tag | BeautifulSoup) -> str:
        """Convert HTML content to Markdown.

        Args:
            content: BeautifulSoup Tag or object.

        Returns:
            Markdown string.
        """
        lines = []

        for element in content.descendants:
            if isinstance(element, str):
                text = element.strip()
                if text:
                    lines.append(text)
            elif hasattr(element, "name"):
                tag = element.name

                if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    level = int(tag[1])
                    text = clean_html_text(element.get_text())
                    if text:
                        lines.append(f"\n{'#' * level} {text}\n")

                elif tag == "p":
                    text = clean_html_text(element.get_text())
                    if text:
                        lines.append(f"\n{text}\n")

                elif tag in ["ul", "ol"]:
                    for i, li in enumerate(element.find_all("li", recursive=False)):
                        text = clean_html_text(li.get_text())
                        if text:
                            prefix = f"{i + 1}." if tag == "ol" else "-"
                            lines.append(f"{prefix} {text}")
                    lines.append("")

                elif tag == "blockquote":
                    text = clean_html_text(element.get_text())
                    if text:
                        lines.append(f"> {text}\n")

                elif tag == "pre" or tag == "code":
                    text = element.get_text()
                    if text:
                        lines.append(f"\n```\n{text}\n```\n")

        # Clean up and join
        markdown = "\n".join(lines)

        # Remove excessive newlines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        return markdown.strip()
