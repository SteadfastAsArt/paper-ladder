"""Unified data models for Paper-Ladder."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Paper(BaseModel):
    """Represents an academic paper with metadata from various sources."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    doi: str | None = None
    year: int | None = None
    journal: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    source: str
    raw_data: dict[str, Any] = Field(default_factory=dict)

    # Additional metadata
    citations_count: int | None = None
    references_count: int | None = None
    open_access: bool | None = None
    keywords: list[str] = Field(default_factory=list)

    def __hash__(self) -> int:
        """Hash based on DOI or title for deduplication."""
        if self.doi:
            return hash(self.doi.lower())
        return hash(self.title.lower())

    def __eq__(self, other: object) -> bool:
        """Check equality based on DOI or title."""
        if not isinstance(other, Paper):
            return False
        if self.doi and other.doi:
            return self.doi.lower() == other.doi.lower()
        return self.title.lower() == other.title.lower()


class Author(BaseModel):
    """Represents an author with metadata."""

    name: str
    source_id: str | None = None
    source: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    orcid: str | None = None
    url: str | None = None
    paper_count: int | None = None
    citation_count: int | None = None
    h_index: int | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class Institution(BaseModel):
    """Represents an institution/affiliation."""

    name: str
    source_id: str | None = None
    source: str | None = None
    country: str | None = None
    type: str | None = None  # e.g., "education", "company", "government"
    url: str | None = None
    paper_count: int | None = None
    citation_count: int | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ExtractedContent(BaseModel):
    """Represents extracted content from a paper."""

    markdown: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    figures: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_type: str | None = None  # "pdf" or "html"


class SearchResult(BaseModel):
    """Represents a search result with papers from multiple sources."""

    query: str
    papers: list[Paper] = Field(default_factory=list)
    total_results: int | None = None
    sources_queried: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Structured Content Models (for PDF extraction)
# ============================================================================


class ContentBlock(BaseModel):
    """A single content block extracted from a document."""

    type: str  # "text", "title", "table", "image", "equation", "list"
    content: str  # Text content or reference path for images
    text_level: int = 0  # 0=body, 1=h1, 2=h2, etc.
    page_idx: int | None = None
    bbox: list[float] | None = None  # [x0, y0, x1, y1] normalized 0-1000
    raw_data: dict[str, Any] = Field(default_factory=dict)


class Section(BaseModel):
    """A document section with title and content blocks."""

    title: str
    level: int = 1  # Heading level (1=h1, 2=h2, etc.)
    blocks: list[ContentBlock] = Field(default_factory=list)
    subsections: list[Section] = Field(default_factory=list)

    def get_text(self) -> str:
        """Get all text content in this section (excluding subsections)."""
        return "\n\n".join(block.content for block in self.blocks if block.type == "text")

    def get_all_text(self) -> str:
        """Get all text content including subsections."""
        parts = [self.get_text()]
        for sub in self.subsections:
            parts.append(sub.get_all_text())
        return "\n\n".join(p for p in parts if p)


class DocumentStructure(BaseModel):
    """Base structured document with hierarchical sections."""

    title: str | None = None
    sections: list[Section] = Field(default_factory=list)
    all_blocks: list[ContentBlock] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_path: str | None = None
    document_type: str = "generic"  # "paper" or "book"

    def get_section(self, title_pattern: str) -> Section | None:
        """Find a section by title pattern (case-insensitive partial match)."""
        pattern = title_pattern.lower()
        for section in self.sections:
            if pattern in section.title.lower():
                return section
        return None

    def get_all_sections_flat(self) -> list[Section]:
        """Get all sections flattened (including nested subsections)."""
        result = []

        def _collect(sections: list[Section]) -> None:
            for s in sections:
                result.append(s)
                _collect(s.subsections)

        _collect(self.sections)
        return result


class PaperStructure(DocumentStructure):
    """Structured academic paper with standard sections."""

    document_type: str = "paper"

    # Standard paper sections (populated if detected)
    abstract: str | None = None
    introduction: str | None = None
    methods: str | None = None  # Also matches "methodology", "materials and methods"
    results: str | None = None
    discussion: str | None = None
    conclusion: str | None = None
    references_text: str | None = None  # Raw references section text
    acknowledgments: str | None = None

    # Detected authors and affiliations from content
    detected_authors: list[str] = Field(default_factory=list)
    detected_affiliations: list[str] = Field(default_factory=list)


class ChapterNode(BaseModel):
    """A chapter/section node in a book structure."""

    title: str
    level: int  # 1=chapter, 2=section, 3=subsection, etc.
    page_start: int | None = None
    content: str = ""  # Direct text content
    blocks: list[ContentBlock] = Field(default_factory=list)
    children: list[ChapterNode] = Field(default_factory=list)

    def get_all_text(self) -> str:
        """Get all text content including children."""
        parts = [self.content]
        parts.extend(b.content for b in self.blocks if b.type == "text")
        for child in self.children:
            parts.append(child.get_all_text())
        return "\n\n".join(p for p in parts if p)


class BookStructure(DocumentStructure):
    """Structured textbook with chapter hierarchy."""

    document_type: str = "book"

    # Book-specific fields
    chapters: list[ChapterNode] = Field(default_factory=list)
    toc: list[dict[str, Any]] = Field(default_factory=list)  # Table of contents

    def get_chapter(self, title_pattern: str) -> ChapterNode | None:
        """Find a chapter by title pattern."""
        pattern = title_pattern.lower()

        def _find(nodes: list[ChapterNode]) -> ChapterNode | None:
            for node in nodes:
                if pattern in node.title.lower():
                    return node
                found = _find(node.children)
                if found:
                    return found
            return None

        return _find(self.chapters)

    def get_all_chapters_flat(self) -> list[ChapterNode]:
        """Get all chapters/sections flattened."""
        result = []

        def _collect(nodes: list[ChapterNode]) -> None:
            for n in nodes:
                result.append(n)
                _collect(n.children)

        _collect(self.chapters)
        return result
