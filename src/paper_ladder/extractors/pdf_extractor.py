"""PDF content extractor using MinerU for Paper-Ladder."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Literal

import httpx

from paper_ladder.extractors.base import BaseExtractor
from paper_ladder.models import BookStructure, ExtractedContent, PaperStructure
from paper_ladder.utils import is_valid_url


class PDFExtractor(BaseExtractor):
    """PDF content extractor using MinerU.

    MinerU is a tool for extracting structured content from PDFs,
    including text, figures, and tables.
    """

    name = "pdf"
    supported_extensions = ["pdf"]

    def can_handle(self, source: str | Path) -> bool:
        """Check if this extractor can handle the given source.

        Args:
            source: URL or file path to check.

        Returns:
            True if this is a PDF file or URL.
        """
        source_str = str(source).lower()
        ext = self._get_extension(source)
        return ext == "pdf" or "/pdf/" in source_str or source_str.endswith(".pdf")

    async def extract(
        self,
        source: str | Path,
        output_dir: str | Path | None = None,
        **kwargs: object,
    ) -> ExtractedContent:
        """Extract content from a PDF file or URL.

        Args:
            source: URL or file path to the PDF.
            output_dir: Directory to save extracted figures.
            **kwargs: Additional parameters for MinerU.

        Returns:
            ExtractedContent with markdown and extracted elements.
        """
        source_str = str(source)

        # If source is a URL, download it first
        if is_valid_url(source_str):
            pdf_path = await self._download_pdf(source_str)
            source_type = "pdf_url"
        else:
            pdf_path = Path(source)
            source_type = "pdf_file"

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Set up output directory
        if output_dir is None:
            output_dir = Path(self.config.output_dir) / "extracted"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run MinerU extraction
        result = await self._run_mineru(pdf_path, output_dir, **kwargs)

        return ExtractedContent(
            markdown=result["markdown"],
            metadata=result.get("metadata", {}),
            figures=result.get("figures", []),
            tables=result.get("tables", []),
            source_url=source_str if is_valid_url(source_str) else None,
            source_type=source_type,
        )

    async def extract_structured(
        self,
        source: str | Path,
        document_type: Literal["paper", "book", "auto"] = "auto",
        output_dir: str | Path | None = None,
    ) -> PaperStructure | BookStructure:
        """Extract structured content from a PDF with section parsing.

        This method provides semantically structured output, automatically
        identifying sections like abstract, introduction, methods, etc. for
        papers, or building a chapter hierarchy for books.

        Args:
            source: URL or file path to the PDF.
            document_type: Type of document:
                - "paper": Academic paper with standard sections
                - "book": Textbook with chapter hierarchy
                - "auto": Auto-detect based on content
            output_dir: Directory to save extracted figures.

        Returns:
            PaperStructure for papers, BookStructure for books.

        Example:
            >>> async with PDFExtractor() as extractor:
            ...     paper = await extractor.extract_structured("paper.pdf", "paper")
            ...     print(paper.abstract)
            ...     print(paper.introduction)
            ...
            >>> async with PDFExtractor() as extractor:
            ...     book = await extractor.extract_structured("textbook.pdf", "book")
            ...     for chapter in book.chapters:
            ...         print(f"{chapter.title}: {len(chapter.children)} sections")
        """
        from paper_ladder.extractors.structured_extractor import StructuredExtractor

        extractor = StructuredExtractor(config=self.config)
        return await extractor.extract(source, document_type, output_dir)

    async def _download_pdf(self, url: str) -> Path:
        """Download a PDF from a URL to a temporary file.

        Args:
            url: URL to download from.

        Returns:
            Path to the downloaded PDF.
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

            # Create temp file with .pdf extension
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            )
            temp_file.write(response.content)
            temp_file.close()

            return Path(temp_file.name)

    async def _run_mineru(
        self,
        pdf_path: Path,
        output_dir: Path,
        **kwargs: object,
    ) -> dict[str, Any]:
        """Run MinerU extraction on a PDF.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Directory to save extracted content.
            **kwargs: Additional MinerU parameters.

        Returns:
            Dict with markdown, metadata, figures, and tables.
        """
        # Run in executor to not block the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._mineru_extract_sync,
            pdf_path,
            output_dir,
            kwargs,
        )

    def _mineru_extract_sync(
        self,
        pdf_path: Path,
        output_dir: Path,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous MinerU extraction (runs in thread pool).

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Directory to save extracted content.
            options: Additional extraction options.

        Returns:
            Dict with markdown, metadata, figures, and tables.
        """
        try:
            from mineru.cli.common import do_parse
        except ImportError as e:
            raise ImportError(
                "MinerU is required for PDF extraction. "
                "Install with: pip install mineru"
            ) from e

        # Read PDF bytes
        pdf_bytes = pdf_path.read_bytes()
        pdf_name = pdf_path.stem

        # Run extraction using MinerU's do_parse function
        do_parse(
            output_dir=str(output_dir),
            pdf_file_names=[pdf_name],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=["en"],
            backend="pipeline",
            parse_method="auto",
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,
            f_dump_middle_json=False,
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=True,
        )

        # Read the generated markdown file
        md_path = output_dir / pdf_name / "auto" / f"{pdf_name}.md"
        markdown = ""
        if md_path.exists():
            markdown = md_path.read_text(encoding="utf-8")

        # Collect figure paths
        image_dir = output_dir / pdf_name / "auto" / "images"
        figures = []
        if image_dir.exists():
            figures = [str(p) for p in image_dir.glob("*.png")]
            figures.extend([str(p) for p in image_dir.glob("*.jpg")])

        # Read content list for tables
        tables = []
        content_list_path = output_dir / pdf_name / "auto" / f"{pdf_name}_content_list.json"
        if content_list_path.exists():
            import json
            content_list = json.loads(content_list_path.read_text(encoding="utf-8"))
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "table":
                    table_html = item.get("html", "")
                    if table_html:
                        tables.append(table_html)

        return {
            "markdown": markdown,
            "metadata": {
                "pdf_path": str(pdf_path),
                "output_dir": str(output_dir),
            },
            "figures": figures,
            "tables": tables,
        }
