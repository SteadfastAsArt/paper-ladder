"""Structured content extractor for papers and books using MinerU."""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

import httpx

from paper_ladder.config import Config, get_config
from paper_ladder.models import (
    BookStructure,
    ChapterNode,
    ContentBlock,
    PaperStructure,
    Section,
)
from paper_ladder.utils import is_valid_url

# Standard section patterns for academic papers
PAPER_SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [r"^abstract$", r"^summary$"],
    "introduction": [r"^introduction$", r"^\d+\.?\s*introduction$"],
    "methods": [
        r"^methods?$",
        r"^methodology$",
        r"^materials?\s*(and|&)\s*methods?$",
        r"^experimental\s*(section|methods?)?$",
        r"^\d+\.?\s*methods?$",
    ],
    "results": [
        r"^results?$",
        r"^findings$",
        r"^results?\s*(and|&)\s*discussion$",
        r"^\d+\.?\s*results?$",
    ],
    "discussion": [r"^discussion$", r"^\d+\.?\s*discussion$"],
    "conclusion": [
        r"^conclusions?$",
        r"^concluding\s*remarks?$",
        r"^\d+\.?\s*conclusions?$",
    ],
    "references": [
        r"^references?$",
        r"^bibliography$",
        r"^literature\s*cited$",
        r"^\d+\.?\s*references?$",
    ],
    "acknowledgments": [
        r"^acknowledgm?ents?$",
        r"^acknowledgements?$",
    ],
}


def _match_section_type(title: str) -> str | None:
    """Match a title to a standard paper section type."""
    title_clean = title.strip().lower()
    for section_type, patterns in PAPER_SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, title_clean, re.IGNORECASE):
                return section_type
    return None


class StructuredExtractor:
    """Extract structured content from PDFs using MinerU.

    Supports two document types:
    - "paper": Academic papers with standard sections (abstract, intro, etc.)
    - "book": Textbooks with hierarchical chapter structure
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()

    async def extract(
        self,
        source: str | Path,
        document_type: Literal["paper", "book", "auto"] = "auto",
        output_dir: str | Path | None = None,
    ) -> PaperStructure | BookStructure:
        """Extract structured content from a PDF.

        Args:
            source: URL or file path to the PDF.
            document_type: Type of document ("paper", "book", or "auto").
            output_dir: Directory to save extracted figures.

        Returns:
            PaperStructure for papers, BookStructure for books.
        """
        source_str = str(source)

        # Download if URL
        if is_valid_url(source_str):
            pdf_path = await self._download_pdf(source_str)
        else:
            pdf_path = Path(source)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Set up output directory
        if output_dir is None:
            output_dir = Path(self.config.output_dir) / "structured"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run MinerU extraction
        raw_result = await self._run_mineru(pdf_path, output_dir)

        # Parse content blocks
        blocks = self._parse_content_blocks(raw_result)

        # Auto-detect document type if needed
        if document_type == "auto":
            document_type = self._detect_document_type(blocks)

        # Build structured output
        if document_type == "paper":
            return self._build_paper_structure(blocks, raw_result, source_str)
        else:
            return self._build_book_structure(blocks, raw_result, source_str)

    async def _download_pdf(self, url: str) -> Path:
        """Download a PDF from a URL."""
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
            temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_file.write(response.content)
            temp_file.close()
            return Path(temp_file.name)

    async def _run_mineru(
        self,
        pdf_path: Path,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Run MinerU extraction with full JSON output."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._mineru_extract_sync,
            pdf_path,
            output_dir,
        )

    def _mineru_extract_sync(
        self,
        pdf_path: Path,
        output_dir: Path,
    ) -> dict[str, Any]:
        """Synchronous MinerU extraction."""
        try:
            from mineru.cli.common import do_parse
        except ImportError as e:
            raise ImportError(
                "MinerU is required for PDF extraction. Install with: pip install mineru"
            ) from e

        pdf_bytes = pdf_path.read_bytes()
        pdf_name = pdf_path.stem

        # Run extraction with full JSON output
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
            f_dump_middle_json=True,  # Enable full structured JSON
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=True,
        )

        result: dict[str, Any] = {
            "pdf_path": str(pdf_path),
            "pdf_name": pdf_name,
            "output_dir": str(output_dir),
        }

        # Read markdown
        md_path = output_dir / pdf_name / "auto" / f"{pdf_name}.md"
        if md_path.exists():
            result["markdown"] = md_path.read_text(encoding="utf-8")

        # Read content_list.json (simplified structure)
        content_list_path = output_dir / pdf_name / "auto" / f"{pdf_name}_content_list.json"
        if content_list_path.exists():
            result["content_list"] = json.loads(content_list_path.read_text(encoding="utf-8"))

        # Read middle.json (full structure)
        middle_json_path = output_dir / pdf_name / "auto" / f"{pdf_name}_middle.json"
        if middle_json_path.exists():
            result["middle_json"] = json.loads(middle_json_path.read_text(encoding="utf-8"))

        # Collect figures
        image_dir = output_dir / pdf_name / "auto" / "images"
        figures = []
        if image_dir.exists():
            figures = [str(p) for p in image_dir.glob("*.png")]
            figures.extend([str(p) for p in image_dir.glob("*.jpg")])
        result["figures"] = figures

        return result

    def _parse_content_blocks(self, raw_result: dict[str, Any]) -> list[ContentBlock]:
        """Parse MinerU output into ContentBlock list."""
        blocks: list[ContentBlock] = []

        # Prefer content_list (simpler structure)
        content_list = raw_result.get("content_list", [])
        if content_list:
            for item in content_list:
                if not isinstance(item, dict):
                    continue

                block_type = item.get("type", "text")
                content = ""
                text_level = 0

                if block_type == "text":
                    content = item.get("text", "")
                    text_level = item.get("text_level", 0)
                    # Infer title from text_level
                    if text_level > 0:
                        block_type = "title"
                elif block_type == "image":
                    content = item.get("img_path", "")
                elif block_type == "table":
                    content = item.get("html", "") or item.get("latex", "")
                elif block_type == "equation":
                    content = item.get("latex", "")

                if content or block_type in ("image", "table"):
                    blocks.append(
                        ContentBlock(
                            type=block_type,
                            content=content,
                            text_level=text_level,
                            page_idx=item.get("page_idx"),
                            bbox=item.get("bbox"),
                            raw_data=item,
                        )
                    )
            return blocks

        # Fallback: parse middle_json
        middle = raw_result.get("middle_json", {})
        pdf_info = middle.get("pdf_info", [])

        for page_info in pdf_info:
            page_idx = page_info.get("page_idx", 0)
            para_blocks = page_info.get("para_blocks", [])

            for para in para_blocks:
                block = self._parse_para_block(para, page_idx)
                if block:
                    blocks.append(block)

        return blocks

    def _parse_para_block(self, para: dict[str, Any], page_idx: int) -> ContentBlock | None:
        """Parse a paragraph block from middle.json."""
        block_type = para.get("type", "text")
        text_level = para.get("text_level", 0)
        bbox = para.get("bbox")

        # Extract text from nested structure
        content = ""
        if "lines" in para:
            for line in para["lines"]:
                for span in line.get("spans", []):
                    if span.get("type") == "text":
                        content += span.get("content", "") + " "
        elif "text" in para:
            content = para["text"]

        content = content.strip()
        if not content and block_type == "text":
            return None

        # Detect title based on text_level
        if text_level > 0 and block_type == "text":
            block_type = "title"

        return ContentBlock(
            type=block_type,
            content=content,
            text_level=text_level,
            page_idx=page_idx,
            bbox=bbox,
            raw_data=para,
        )

    def _detect_document_type(self, blocks: list[ContentBlock]) -> Literal["paper", "book"]:
        """Auto-detect document type based on content patterns."""
        title_blocks = [b for b in blocks if b.type == "title"]
        title_texts = [b.content.lower() for b in title_blocks]

        # Check for paper patterns
        paper_indicators = 0
        for title in title_texts:
            if _match_section_type(title):
                paper_indicators += 1

        # Check for book patterns (numbered chapters, "Chapter X")
        book_indicators = 0
        for title in title_texts:
            if re.match(r"^chapter\s+\d+", title, re.IGNORECASE):
                book_indicators += 2
            elif re.match(r"^\d+\.\d+", title):  # 1.1, 2.3 numbering
                book_indicators += 1

        # More pages usually means book
        max_page = max((b.page_idx or 0 for b in blocks), default=0)
        if max_page > 50:
            book_indicators += 2

        return "book" if book_indicators > paper_indicators else "paper"

    def _build_paper_structure(
        self,
        blocks: list[ContentBlock],
        raw_result: dict[str, Any],
        source_path: str,
    ) -> PaperStructure:
        """Build PaperStructure from content blocks."""
        sections: list[Section] = []
        current_section: Section | None = None
        pre_section_blocks: list[ContentBlock] = []  # Blocks before first section

        # Build sections from blocks
        for block in blocks:
            if block.type == "title" and block.text_level > 0:
                # Start new section
                if current_section:
                    sections.append(current_section)
                current_section = Section(
                    title=block.content,
                    level=block.text_level,
                    blocks=[],
                )
            elif current_section:
                current_section.blocks.append(block)
            else:
                pre_section_blocks.append(block)

        # Don't forget last section
        if current_section:
            sections.append(current_section)

        # Extract standard paper sections
        paper = PaperStructure(
            title=self._extract_title(pre_section_blocks, blocks),
            sections=sections,
            all_blocks=blocks,
            figures=raw_result.get("figures", []),
            tables=self._extract_tables(blocks),
            metadata={"pdf_path": raw_result.get("pdf_path")},
            source_path=source_path,
        )

        # Populate standard section fields
        for section in sections:
            section_type = _match_section_type(section.title)
            if section_type == "abstract":
                paper.abstract = section.get_text()
            elif section_type == "introduction":
                paper.introduction = section.get_text()
            elif section_type == "methods":
                paper.methods = section.get_text()
            elif section_type == "results":
                paper.results = section.get_text()
            elif section_type == "discussion":
                paper.discussion = section.get_text()
            elif section_type == "conclusion":
                paper.conclusion = section.get_text()
            elif section_type == "references":
                paper.references_text = section.get_text()
            elif section_type == "acknowledgments":
                paper.acknowledgments = section.get_text()

        # Try to detect abstract from pre-section content if not found
        if not paper.abstract and pre_section_blocks:
            abstract_text = self._find_abstract_in_blocks(pre_section_blocks)
            if abstract_text:
                paper.abstract = abstract_text

        return paper

    def _build_book_structure(
        self,
        blocks: list[ContentBlock],
        raw_result: dict[str, Any],
        source_path: str,
    ) -> BookStructure:
        """Build BookStructure with chapter hierarchy."""
        chapters: list[ChapterNode] = []
        chapter_stack: list[ChapterNode] = []  # Stack for nesting

        for block in blocks:
            if block.type == "title" and block.text_level > 0:
                node = ChapterNode(
                    title=block.content,
                    level=block.text_level,
                    page_start=block.page_idx,
                    blocks=[],
                )

                # Find parent based on level
                while chapter_stack and chapter_stack[-1].level >= block.text_level:
                    chapter_stack.pop()

                if chapter_stack:
                    # Add as child of parent
                    chapter_stack[-1].children.append(node)
                else:
                    # Top-level chapter
                    chapters.append(node)

                chapter_stack.append(node)

            elif chapter_stack:
                # Add content to current chapter
                chapter_stack[-1].blocks.append(block)

        # Convert to Section list for base class compatibility
        sections = [
            Section(
                title=ch.title,
                level=ch.level,
                blocks=ch.blocks,
            )
            for ch in chapters
        ]

        return BookStructure(
            title=self._extract_title([], blocks),
            sections=sections,
            all_blocks=blocks,
            chapters=chapters,
            figures=raw_result.get("figures", []),
            tables=self._extract_tables(blocks),
            metadata={"pdf_path": raw_result.get("pdf_path")},
            source_path=source_path,
        )

    def _extract_title(
        self,
        pre_section_blocks: list[ContentBlock],
        all_blocks: list[ContentBlock],
    ) -> str | None:
        """Extract document title from blocks."""
        # Usually the first large title (text_level=1) on page 0
        for block in pre_section_blocks:
            if block.type == "title" and block.page_idx == 0:
                return block.content

        # Fallback: first title block overall
        for block in all_blocks:
            if block.type == "title":
                return block.content

        return None

    def _extract_tables(self, blocks: list[ContentBlock]) -> list[str]:
        """Extract table content from blocks."""
        return [b.content for b in blocks if b.type == "table" and b.content]

    def _find_abstract_in_blocks(self, blocks: list[ContentBlock]) -> str | None:
        """Try to find abstract text in early blocks."""
        text_blocks = [b for b in blocks if b.type == "text" and b.content]

        # Look for block starting with "Abstract"
        for block in text_blocks:
            if block.content.lower().startswith("abstract"):
                # Remove "Abstract" prefix
                text = re.sub(r"^abstract[:\s]*", "", block.content, flags=re.IGNORECASE)
                return text.strip()

        # If first few blocks look like abstract (short paragraphs on page 0)
        page0_text = [b.content for b in text_blocks if b.page_idx == 0 and len(b.content) > 50]
        if page0_text and len(page0_text[0]) < 2000:
            return page0_text[0]

        return None
