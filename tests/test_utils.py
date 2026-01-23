"""Tests for utility functions."""

from paper_ladder.utils import (
    clean_html_text,
    extract_year_from_date,
    is_pdf_url,
    is_valid_url,
    normalize_doi,
    normalize_title,
    truncate_text,
)


class TestNormalizeDoi:
    """Tests for normalize_doi."""

    def test_normalize_plain_doi(self):
        """Test normalizing plain DOI."""
        assert normalize_doi("10.1234/test") == "10.1234/test"

    def test_normalize_doi_with_prefix(self):
        """Test normalizing DOI with URL prefix."""
        assert normalize_doi("https://doi.org/10.1234/test") == "10.1234/test"
        assert normalize_doi("http://doi.org/10.1234/test") == "10.1234/test"
        assert normalize_doi("https://dx.doi.org/10.1234/test") == "10.1234/test"
        assert normalize_doi("doi:10.1234/test") == "10.1234/test"

    def test_normalize_doi_uppercase(self):
        """Test normalizing uppercase DOI."""
        assert normalize_doi("10.1234/TEST") == "10.1234/test"

    def test_normalize_doi_none(self):
        """Test normalizing None."""
        assert normalize_doi(None) is None
        assert normalize_doi("") is None


class TestNormalizeTitle:
    """Tests for normalize_title."""

    def test_normalize_title_basic(self):
        """Test basic title normalization."""
        assert normalize_title("Test Paper") == "test paper"

    def test_normalize_title_whitespace(self):
        """Test title normalization with extra whitespace."""
        assert normalize_title("  Test   Paper  ") == "test paper"

    def test_normalize_title_newlines(self):
        """Test title normalization with newlines."""
        assert normalize_title("Test\n\nPaper") == "test paper"


class TestExtractYearFromDate:
    """Tests for extract_year_from_date."""

    def test_extract_year_yyyy(self):
        """Test extracting year from YYYY format."""
        assert extract_year_from_date("2024") == 2024

    def test_extract_year_iso(self):
        """Test extracting year from ISO format."""
        assert extract_year_from_date("2024-01-15") == 2024

    def test_extract_year_text(self):
        """Test extracting year from text."""
        assert extract_year_from_date("January 15, 2024") == 2024

    def test_extract_year_none(self):
        """Test extracting year from None."""
        assert extract_year_from_date(None) is None
        assert extract_year_from_date("") is None


class TestIsValidUrl:
    """Tests for is_valid_url."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert is_valid_url("http://example.com") is True
        assert is_valid_url("https://example.com") is True

    def test_valid_url_with_path(self):
        """Test valid URL with path."""
        assert is_valid_url("https://example.com/path/to/page") is True

    def test_invalid_url(self):
        """Test invalid URLs."""
        assert is_valid_url("not-a-url") is False
        assert is_valid_url("/local/path") is False
        assert is_valid_url("") is False
        assert is_valid_url(None) is False


class TestIsPdfUrl:
    """Tests for is_pdf_url."""

    def test_pdf_extension(self):
        """Test URL with .pdf extension."""
        assert is_pdf_url("https://example.com/paper.pdf") is True
        assert is_pdf_url("https://example.com/paper.PDF") is True

    def test_pdf_path(self):
        """Test URL with /pdf/ in path."""
        assert is_pdf_url("https://example.com/pdf/12345") is True

    def test_not_pdf(self):
        """Test non-PDF URL."""
        assert is_pdf_url("https://example.com/paper.html") is False
        assert is_pdf_url("https://example.com/paper") is False
        assert is_pdf_url(None) is False


class TestTruncateText:
    """Tests for truncate_text."""

    def test_truncate_short_text(self):
        """Test truncating text shorter than max length."""
        assert truncate_text("short", 100) == "short"

    def test_truncate_long_text(self):
        """Test truncating text longer than max length."""
        result = truncate_text("a" * 100, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        """Test truncating with custom suffix."""
        result = truncate_text("a" * 100, 50, suffix="[...]")
        assert result.endswith("[...]")


class TestCleanHtmlText:
    """Tests for clean_html_text."""

    def test_clean_entities(self):
        """Test cleaning HTML entities."""
        assert clean_html_text("&amp;") == "&"
        assert clean_html_text("&lt;") == "<"
        assert clean_html_text("&gt;") == ">"

    def test_clean_tags(self):
        """Test removing HTML tags."""
        assert clean_html_text("<p>text</p>") == "text"
        assert clean_html_text("<a href='#'>link</a>") == "link"

    def test_clean_whitespace(self):
        """Test normalizing whitespace."""
        assert clean_html_text("  multiple   spaces  ") == "multiple spaces"
