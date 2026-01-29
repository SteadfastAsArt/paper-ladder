"""Citation format export for Paper-Ladder.

Supports BibTeX, RIS, and EndNote XML formats.
"""

from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_ladder.models import Paper


def _sanitize_key(text: str) -> str:
    """Generate a safe citation key from text.

    Args:
        text: Text to convert to a key.

    Returns:
        Safe alphanumeric key.
    """
    # Remove accents and normalize
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ASCII", "ignore").decode("ASCII")
    # Keep only alphanumeric characters
    text = re.sub(r"[^a-zA-Z0-9]", "", text)
    return text.lower()


def _escape_bibtex(text: str) -> str:
    """Escape special characters for BibTeX.

    Args:
        text: Text to escape.

    Returns:
        Escaped text.
    """
    # Replace special LaTeX characters
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _escape_xml(text: str) -> str:
    """Escape special characters for XML.

    Args:
        text: Text to escape.

    Returns:
        Escaped text.
    """
    replacements = [
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


class CitationFormatter(ABC):
    """Abstract base class for citation formatters."""

    name: str = "base"
    file_extension: str = ".txt"

    @abstractmethod
    def format(self, paper: Paper) -> str:
        """Format a single paper as a citation.

        Args:
            paper: Paper object to format.

        Returns:
            Formatted citation string.
        """
        ...

    def format_many(self, papers: list[Paper]) -> str:
        """Format multiple papers as citations.

        Args:
            papers: List of Paper objects.

        Returns:
            All citations concatenated with newlines.
        """
        return "\n\n".join(self.format(p) for p in papers)

    def to_file(self, papers: list[Paper] | Paper, path: str | Path) -> Path:
        """Write citations to a file.

        Args:
            papers: Paper(s) to format.
            path: Output file path.

        Returns:
            Path to the written file.
        """
        if isinstance(papers, list):
            content = self.format_many(papers)
        else:
            content = self.format(papers)

        path = Path(path)
        path.write_text(content, encoding="utf-8")
        return path


class BibTeXFormatter(CitationFormatter):
    """Format citations in BibTeX format.

    Example output:
        @article{lecun2015deep,
            title = {Deep learning},
            author = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
            year = {2015},
            journal = {Nature},
            doi = {10.1038/nature14539}
        }
    """

    name: str = "bibtex"
    file_extension: str = ".bib"

    def _generate_key(self, paper: Paper) -> str:
        """Generate a BibTeX citation key.

        Format: firstauthor_lastname + year + first_title_word
        """
        # Get first author's last name
        first_author = ""
        if paper.authors:
            author_parts = paper.authors[0].split()
            if author_parts:
                first_author = _sanitize_key(author_parts[-1])

        # Get year
        year = str(paper.year) if paper.year else ""

        # Get first significant word from title
        title_word = ""
        if paper.title:
            # Skip common articles
            skip_words = {"a", "an", "the", "on", "in", "of", "for", "to", "and"}
            words = paper.title.lower().split()
            for word in words:
                cleaned = _sanitize_key(word)
                if cleaned and cleaned not in skip_words:
                    title_word = cleaned[:10]
                    break

        key = f"{first_author}{year}{title_word}"
        return key if key else "unknown"

    def _format_authors(self, authors: list[str]) -> str:
        """Format authors for BibTeX (separated by ' and ').

        Args:
            authors: List of author names.

        Returns:
            BibTeX-formatted author string.
        """
        return " and ".join(_escape_bibtex(a) for a in authors)

    def format(self, paper: Paper) -> str:
        """Format a paper as BibTeX.

        Args:
            paper: Paper to format.

        Returns:
            BibTeX entry string.
        """
        key = self._generate_key(paper)

        # Determine entry type based on available fields
        if paper.journal:
            entry_type = "article"
        else:
            entry_type = "misc"

        lines = [f"@{entry_type}{{{key},"]

        # Title
        if paper.title:
            lines.append(f"    title = {{{_escape_bibtex(paper.title)}}},")

        # Authors
        if paper.authors:
            lines.append(f"    author = {{{self._format_authors(paper.authors)}}},")

        # Year
        if paper.year:
            lines.append(f"    year = {{{paper.year}}},")

        # Journal
        if paper.journal:
            lines.append(f"    journal = {{{_escape_bibtex(paper.journal)}}},")

        # DOI
        if paper.doi:
            lines.append(f"    doi = {{{paper.doi}}},")

        # URL
        if paper.url:
            lines.append(f"    url = {{{paper.url}}},")

        # Abstract (optional, can be long)
        if paper.abstract:
            # Truncate very long abstracts
            abstract = paper.abstract[:2000] if len(paper.abstract) > 2000 else paper.abstract
            lines.append(f"    abstract = {{{_escape_bibtex(abstract)}}},")

        # Keywords
        if paper.keywords:
            keywords = ", ".join(paper.keywords)
            lines.append(f"    keywords = {{{_escape_bibtex(keywords)}}},")

        # Remove trailing comma from last field
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("}")
        return "\n".join(lines)


class RISFormatter(CitationFormatter):
    """Format citations in RIS format (Research Information Systems).

    Compatible with Zotero, EndNote, Mendeley, and other reference managers.

    Example output:
        TY  - JOUR
        TI  - Deep learning
        AU  - LeCun, Yann
        AU  - Bengio, Yoshua
        PY  - 2015
        JO  - Nature
        DO  - 10.1038/nature14539
        ER  -
    """

    name: str = "ris"
    file_extension: str = ".ris"

    def format(self, paper: Paper) -> str:
        """Format a paper as RIS.

        Args:
            paper: Paper to format.

        Returns:
            RIS entry string.
        """
        lines = []

        # Type tag - JOUR for journal articles, GEN for generic
        if paper.journal:
            lines.append("TY  - JOUR")
        else:
            lines.append("TY  - GEN")

        # Title
        if paper.title:
            lines.append(f"TI  - {paper.title}")

        # Authors (one per line)
        for author in paper.authors:
            lines.append(f"AU  - {author}")

        # Year
        if paper.year:
            lines.append(f"PY  - {paper.year}")

        # Journal
        if paper.journal:
            lines.append(f"JO  - {paper.journal}")

        # DOI
        if paper.doi:
            lines.append(f"DO  - {paper.doi}")

        # URL
        if paper.url:
            lines.append(f"UR  - {paper.url}")

        # Abstract
        if paper.abstract:
            lines.append(f"AB  - {paper.abstract}")

        # Keywords (one per line)
        for keyword in paper.keywords:
            lines.append(f"KW  - {keyword}")

        # Source database
        if paper.source:
            lines.append(f"DB  - {paper.source}")

        # End of record
        lines.append("ER  -")

        return "\n".join(lines)


class EndNoteFormatter(CitationFormatter):
    """Format citations in EndNote XML format.

    Example output:
        <record>
            <ref-type name="Journal Article">17</ref-type>
            <contributors>
                <authors>
                    <author>LeCun, Yann</author>
                </authors>
            </contributors>
            <titles>
                <title>Deep learning</title>
                <secondary-title>Nature</secondary-title>
            </titles>
            <dates>
                <year>2015</year>
            </dates>
            <electronic-resource-num>10.1038/nature14539</electronic-resource-num>
        </record>
    """

    name: str = "endnote"
    file_extension: str = ".xml"

    def format(self, paper: Paper) -> str:
        """Format a paper as EndNote XML.

        Args:
            paper: Paper to format.

        Returns:
            EndNote XML record string.
        """
        lines = ["<record>"]

        # Reference type (17 = Journal Article, 13 = Generic)
        if paper.journal:
            lines.append('    <ref-type name="Journal Article">17</ref-type>')
        else:
            lines.append('    <ref-type name="Generic">13</ref-type>')

        # Authors
        if paper.authors:
            lines.append("    <contributors>")
            lines.append("        <authors>")
            for author in paper.authors:
                lines.append(f"            <author>{_escape_xml(author)}</author>")
            lines.append("        </authors>")
            lines.append("    </contributors>")

        # Titles
        lines.append("    <titles>")
        if paper.title:
            lines.append(f"        <title>{_escape_xml(paper.title)}</title>")
        if paper.journal:
            lines.append(f"        <secondary-title>{_escape_xml(paper.journal)}</secondary-title>")
        lines.append("    </titles>")

        # Dates
        if paper.year:
            lines.append("    <dates>")
            lines.append(f"        <year>{paper.year}</year>")
            lines.append("    </dates>")

        # DOI
        if paper.doi:
            lines.append(f"    <electronic-resource-num>{_escape_xml(paper.doi)}</electronic-resource-num>")

        # URLs
        if paper.url or paper.pdf_url:
            lines.append("    <urls>")
            lines.append("        <related-urls>")
            if paper.url:
                lines.append(f"            <url>{_escape_xml(paper.url)}</url>")
            if paper.pdf_url:
                lines.append(f"            <url>{_escape_xml(paper.pdf_url)}</url>")
            lines.append("        </related-urls>")
            lines.append("    </urls>")

        # Abstract
        if paper.abstract:
            lines.append(f"    <abstract>{_escape_xml(paper.abstract)}</abstract>")

        # Keywords
        if paper.keywords:
            lines.append("    <keywords>")
            for keyword in paper.keywords:
                lines.append(f"        <keyword>{_escape_xml(keyword)}</keyword>")
            lines.append("    </keywords>")

        lines.append("</record>")
        return "\n".join(lines)

    def format_many(self, papers: list[Paper]) -> str:
        """Format multiple papers as EndNote XML.

        Wraps records in an xml/records container.

        Args:
            papers: List of papers.

        Returns:
            Complete EndNote XML document.
        """
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append("<xml>")
        lines.append("<records>")

        for paper in papers:
            lines.append(self.format(paper))

        lines.append("</records>")
        lines.append("</xml>")

        return "\n".join(lines)


# Registry of available formatters
FORMATTERS: dict[str, type[CitationFormatter]] = {
    "bibtex": BibTeXFormatter,
    "bib": BibTeXFormatter,
    "ris": RISFormatter,
    "endnote": EndNoteFormatter,
    "xml": EndNoteFormatter,
}


# Convenience functions


def to_bibtex(papers: list[Paper] | Paper) -> str:
    """Convert paper(s) to BibTeX format.

    Args:
        papers: Paper or list of papers.

    Returns:
        BibTeX formatted string.
    """
    formatter = BibTeXFormatter()
    if isinstance(papers, list):
        return formatter.format_many(papers)
    return formatter.format(papers)


def to_ris(papers: list[Paper] | Paper) -> str:
    """Convert paper(s) to RIS format.

    Args:
        papers: Paper or list of papers.

    Returns:
        RIS formatted string.
    """
    formatter = RISFormatter()
    if isinstance(papers, list):
        return formatter.format_many(papers)
    return formatter.format(papers)


def to_endnote(papers: list[Paper] | Paper) -> str:
    """Convert paper(s) to EndNote XML format.

    Args:
        papers: Paper or list of papers.

    Returns:
        EndNote XML formatted string.
    """
    formatter = EndNoteFormatter()
    if isinstance(papers, list):
        return formatter.format_many(papers)
    return formatter.format(papers)


def export_citations(
    papers: list[Paper] | Paper,
    format: str,
    output_path: str | Path | None = None,
) -> str:
    """Export citations in the specified format.

    Args:
        papers: Paper or list of papers to export.
        format: Output format (bibtex, ris, endnote).
        output_path: Optional file path. If provided, writes to file.

    Returns:
        Formatted citation string.

    Raises:
        ValueError: If format is not supported.
    """
    format_lower = format.lower()
    if format_lower not in FORMATTERS:
        available = ", ".join(FORMATTERS.keys())
        raise ValueError(f"Unknown format: {format}. Available: {available}")

    formatter = FORMATTERS[format_lower]()

    if isinstance(papers, list):
        result = formatter.format_many(papers)
    else:
        result = formatter.format(papers)

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")

    return result


def get_formatter(format: str) -> CitationFormatter:
    """Get a formatter instance by name.

    Args:
        format: Format name (bibtex, ris, endnote).

    Returns:
        Formatter instance.

    Raises:
        ValueError: If format is not supported.
    """
    format_lower = format.lower()
    if format_lower not in FORMATTERS:
        available = ", ".join(FORMATTERS.keys())
        raise ValueError(f"Unknown format: {format}. Available: {available}")

    return FORMATTERS[format_lower]()
