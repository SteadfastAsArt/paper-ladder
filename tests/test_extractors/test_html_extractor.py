"""Tests for HTML extractor."""

import pytest

from paper_ladder.extractors.html_extractor import HTMLExtractor


@pytest.fixture
def extractor():
    """Create HTML extractor."""
    return HTMLExtractor()


class TestHTMLExtractor:
    """Tests for HTMLExtractor."""

    def test_extractor_name(self, extractor):
        """Test extractor has correct name."""
        assert extractor.name == "html"

    def test_can_handle_html_file(self, extractor):
        """Test can handle HTML files."""
        assert extractor.can_handle("test.html")
        assert extractor.can_handle("test.htm")
        assert extractor.can_handle("/path/to/file.html")

    def test_can_handle_url(self, extractor):
        """Test can handle URLs."""
        assert extractor.can_handle("https://example.com/article")
        assert extractor.can_handle("https://example.com/paper.html")
        assert not extractor.can_handle("https://example.com/paper.pdf")

    def test_extract_metadata(self, extractor):
        """Test metadata extraction from HTML."""
        from bs4 import BeautifulSoup

        html = """
        <html>
        <head>
            <title>Test Article</title>
            <meta name="author" content="John Doe">
            <meta name="description" content="Test description">
            <meta name="keywords" content="test, article, research">
            <meta name="citation_doi" content="10.1234/test">
        </head>
        <body></body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        metadata = extractor._extract_metadata(soup)

        assert metadata["title"] == "Test Article"
        assert metadata["author"] == "John Doe"
        assert metadata["description"] == "Test description"
        assert "test" in metadata["keywords"]
        assert metadata["doi"] == "10.1234/test"

    def test_extract_figures(self, extractor):
        """Test figure extraction."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <img src="image1.png">
            <figure>
                <img src="image2.png">
            </figure>
            <img data-src="image3.png">
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        figures = extractor._extract_figures(soup)

        assert "image1.png" in figures
        assert "image2.png" in figures
        assert "image3.png" in figures

    def test_extract_tables(self, extractor):
        """Test table extraction."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <table><tr><td>Data 1</td></tr></table>
            <table><tr><td>Data 2</td></tr></table>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        tables = extractor._extract_tables(soup)

        assert len(tables) == 2
        assert "Data 1" in tables[0]
        assert "Data 2" in tables[1]

    def test_html_to_markdown_headings(self, extractor):
        """Test heading conversion to markdown."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <h1>Heading 1</h1>
            <h2>Heading 2</h2>
            <h3>Heading 3</h3>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        markdown = extractor._html_to_markdown(soup)

        assert "# Heading 1" in markdown
        assert "## Heading 2" in markdown
        assert "### Heading 3" in markdown

    def test_html_to_markdown_paragraphs(self, extractor):
        """Test paragraph conversion to markdown."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        markdown = extractor._html_to_markdown(soup)

        assert "First paragraph." in markdown
        assert "Second paragraph." in markdown

    def test_html_to_markdown_lists(self, extractor):
        """Test list conversion to markdown."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
            <ol>
                <li>First</li>
                <li>Second</li>
            </ol>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        markdown = extractor._html_to_markdown(soup)

        assert "- Item 1" in markdown
        assert "- Item 2" in markdown
        assert "1. First" in markdown
        assert "2. Second" in markdown
