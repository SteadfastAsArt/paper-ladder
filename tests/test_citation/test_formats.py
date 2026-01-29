"""Tests for citation format export."""

import pytest

from paper_ladder.citation import (
    BibTeXFormatter,
    EndNoteFormatter,
    RISFormatter,
    export_citations,
    get_formatter,
    to_bibtex,
    to_endnote,
    to_ris,
)
from paper_ladder.models import Paper


class TestBibTeXFormatter:
    """Tests for BibTeX format export."""

    def test_format_basic(self, sample_paper):
        """Test basic BibTeX formatting."""
        formatter = BibTeXFormatter()
        result = formatter.format(sample_paper)

        assert "@article{" in result
        assert "title = {Deep Learning}" in result
        assert "doi = {10.1038/nature14539}" in result
        assert "year = {2015}" in result

    def test_format_authors(self, sample_paper):
        """Test author formatting in BibTeX."""
        formatter = BibTeXFormatter()
        result = formatter.format(sample_paper)

        assert "author = {Yann LeCun and Yoshua Bengio and Geoffrey Hinton}" in result

    def test_format_journal(self, sample_paper):
        """Test journal formatting in BibTeX."""
        formatter = BibTeXFormatter()
        result = formatter.format(sample_paper)

        assert "journal = {Nature}" in result

    def test_format_minimal_paper(self, sample_paper_minimal):
        """Test formatting a minimal paper."""
        formatter = BibTeXFormatter()
        result = formatter.format(sample_paper_minimal)

        assert "@" in result
        assert "title = {Test Paper}" in result

    def test_format_many(self, sample_papers):
        """Test formatting multiple papers."""
        formatter = BibTeXFormatter()
        result = formatter.format_many(sample_papers)

        assert result.count("@article{") >= 1 or result.count("@misc{") >= 1
        assert "Deep Learning" in result
        assert "Attention Is All You Need" in result

    def test_escape_special_chars(self):
        """Test escaping special LaTeX characters."""
        paper = Paper(
            title="Test & Paper with 100% Special Characters",
            source="test",
        )
        formatter = BibTeXFormatter()
        result = formatter.format(paper)

        assert r"\&" in result
        assert r"\%" in result


class TestRISFormatter:
    """Tests for RIS format export."""

    def test_format_basic(self, sample_paper):
        """Test basic RIS formatting."""
        formatter = RISFormatter()
        result = formatter.format(sample_paper)

        assert "TY  - JOUR" in result
        assert "TI  - Deep Learning" in result
        assert "DO  - 10.1038/nature14539" in result
        assert "PY  - 2015" in result
        assert "ER  -" in result

    def test_format_authors(self, sample_paper):
        """Test author formatting in RIS."""
        formatter = RISFormatter()
        result = formatter.format(sample_paper)

        assert "AU  - Yann LeCun" in result
        assert "AU  - Yoshua Bengio" in result
        assert "AU  - Geoffrey Hinton" in result

    def test_format_journal(self, sample_paper):
        """Test journal formatting in RIS."""
        formatter = RISFormatter()
        result = formatter.format(sample_paper)

        assert "JO  - Nature" in result

    def test_format_minimal(self, sample_paper_minimal):
        """Test formatting a minimal paper."""
        formatter = RISFormatter()
        result = formatter.format(sample_paper_minimal)

        assert "TY  -" in result
        assert "TI  - Test Paper" in result
        assert "ER  -" in result


class TestEndNoteFormatter:
    """Tests for EndNote XML format export."""

    def test_format_basic(self, sample_paper):
        """Test basic EndNote XML formatting."""
        formatter = EndNoteFormatter()
        result = formatter.format(sample_paper)

        assert "<record>" in result
        assert "</record>" in result
        assert "<title>Deep Learning</title>" in result
        assert "<year>2015</year>" in result

    def test_format_authors(self, sample_paper):
        """Test author formatting in EndNote XML."""
        formatter = EndNoteFormatter()
        result = formatter.format(sample_paper)

        assert "<author>Yann LeCun</author>" in result
        assert "<author>Yoshua Bengio</author>" in result
        assert "<author>Geoffrey Hinton</author>" in result

    def test_format_many_with_wrapper(self, sample_papers):
        """Test that format_many includes XML wrapper."""
        formatter = EndNoteFormatter()
        result = formatter.format_many(sample_papers)

        assert '<?xml version="1.0"' in result
        assert "<xml>" in result
        assert "<records>" in result
        assert "</records>" in result
        assert "</xml>" in result

    def test_escape_xml_chars(self):
        """Test escaping XML special characters."""
        paper = Paper(
            title="Test <Paper> with & Special Characters",
            source="test",
        )
        formatter = EndNoteFormatter()
        result = formatter.format(paper)

        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_to_bibtex(self, sample_paper):
        """Test to_bibtex convenience function."""
        result = to_bibtex(sample_paper)
        assert "@article{" in result or "@misc{" in result

    def test_to_bibtex_list(self, sample_papers):
        """Test to_bibtex with list of papers."""
        result = to_bibtex(sample_papers)
        assert "Deep Learning" in result
        assert "Attention" in result

    def test_to_ris(self, sample_paper):
        """Test to_ris convenience function."""
        result = to_ris(sample_paper)
        assert "TY  -" in result

    def test_to_endnote(self, sample_paper):
        """Test to_endnote convenience function."""
        result = to_endnote(sample_paper)
        assert "<record>" in result

    def test_export_citations_bibtex(self, sample_paper):
        """Test export_citations with bibtex format."""
        result = export_citations(sample_paper, "bibtex")
        assert "@" in result

    def test_export_citations_ris(self, sample_paper):
        """Test export_citations with ris format."""
        result = export_citations(sample_paper, "ris")
        assert "TY  -" in result

    def test_export_citations_invalid_format(self, sample_paper):
        """Test export_citations with invalid format."""
        with pytest.raises(ValueError, match="Unknown format"):
            export_citations(sample_paper, "invalid")

    def test_get_formatter(self):
        """Test get_formatter function."""
        formatter = get_formatter("bibtex")
        assert isinstance(formatter, BibTeXFormatter)

        formatter = get_formatter("ris")
        assert isinstance(formatter, RISFormatter)

        formatter = get_formatter("endnote")
        assert isinstance(formatter, EndNoteFormatter)

    def test_get_formatter_invalid(self):
        """Test get_formatter with invalid format."""
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("invalid")
