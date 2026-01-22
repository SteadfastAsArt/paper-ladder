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
